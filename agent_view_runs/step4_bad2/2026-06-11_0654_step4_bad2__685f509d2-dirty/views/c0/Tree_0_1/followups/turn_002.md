## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Pr[UFCMA(RO).distinguish() @ &m : res \/ UFCMA.bad2] =
Pr[UFCMA3(RO).distinguish() @ &m : res]
[385|check]>
```

## Opener — reduce the probability goal

**Goal shape:** a goal relating 2 `Pr[...]` terms

**Reduce with:**
- `byequiv (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a pRHL `equiv`
- `byphoare (_: <pre> ==> <post>)` — reduce a single `Pr[...]` to a `phoare` bound
- `rewrite (<a Pr (in)equality lemma> &m …)` — replace ONE `Pr[...]` term with an equal one; byequiv/byphoare reduce a single program, but this goal relates several Pr terms, so reduce them one at a time

**Yours:** which reduction form fits this goal's Pr shape, the pre/post, the numeric bound.

## Status
remaining **2** · phase `probability` / `pr`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Current Pr equality may need a manager-verified bridge route (game-hop or scheme/endpoint normalization) before direct …
  submit `{"intent": "inspect_context", "payload": {"topic": "pr_bridge_routes"}}`
- Need pRHL/procedure-equivalence bridge lemma names or context after checking pr_bridge_routes.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need local lemma hints before choosing a Pr-level proof route.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need exact byphoare/phoare-loop tactic syntax before choosing the probability route.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "while"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `have -> : Pr[UFCMA(ROIN.RO).distinguish() @ &m : res \/ UFCMA.bad2] = Pr[UFCMA3…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/cc_step4_bad2_fable_l4np/l4_checked_action_surface/cc_step4_bad2_l4np/r01/2026-06-10_2344_step4_bad2/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
