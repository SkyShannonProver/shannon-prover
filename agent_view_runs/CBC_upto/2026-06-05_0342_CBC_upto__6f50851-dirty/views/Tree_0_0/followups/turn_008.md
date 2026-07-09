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
{"turn":8,"handled_intent":{"intent":"inspect_context","payload":{"topic":"tactic_forms","name":"byequiv"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect tactic forms","outcome":"The manager returned read-only context for the current goal.","timing":"207 ms","content":{"preview":"=== `byequiv` tactic \u2014 argument forms === Current proof mode: probability Form 1: byequiv => //. Use when: Convert a `Pr[G1.main() @ &m : res] = Pr[G2.main() @ &m : res]` or `Pr[...] <= Pr[...]` goal into an equiv goal that EC can check with `proc; inline *; sim/;auto`. The `=> //` closes any trivial side-conditions (like initial glob equalities) by `trivial`. Example: byequiv => //. (* opens equiv goal *) Form 2: byequiv LEMMA. Use when: Use a pre-declared equiv lemma to close the Pr equality in one step. The lemma's statement must match the two Pr terms. Example: byequiv H_main. Form 3: byequiv LEMMA => //. Use when: Combine: apply lemma + close trivial side-conditions. Example: byequiv H_main => //. Form 4: byequiv (_: PRE ==> POST). Use when: Specify custom PRE/POST for the equiv goal (different from defaults `={glob A}` / `={res}`). Example: byequiv (_: ={glob A} ==> res{1} => res{2} \\/ bad{2}). \u26a0\ufe0f Common mistake: Using `byequiv => //.` on a goal that's NOT a Pr-equality (e.g., `Pr + Pr <= Pr + Pr`). EC reports `invalid goal shape`. Apply `apply ler_add` / `apply ler_add2l` to split the sum first, then `byequiv` on each Pr. See also: byphoare, bypr, apply (run `-tactic-form..."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
