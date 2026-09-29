## Requested: `lookup_symbol` — parseK

[WHERE-HIT] parseK (kind: lemma · admit) * In [lemmas or axioms]: lemma parseK: forall (r : rand) (p : ptxt), parse (r || p) = (r, p). PROOF STATUS: `admit` — this lemma is declared but its proof body is `admit.` in the in-scope source (still citable in EC; you would be relying on an unproven obligation).

## 🎯 Current Goal
```
Current goal

Type variables: <none>

r: rand
p: ptxt
r': rand
p': ptxt
------------------------------------------------------------------------
(r || p) = (r' || p') => (r, p) = (r', p')
```

## Pure Logic — close with smt / rewrite

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **1** · phase `ambient_logic` / `ambient_logic`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- probe `by move=> h; rewrite -(parseK r p) -(parseK r' p') h.` → probed (read-only; state unchanged)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `lookup_symbol`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d3_formatI/r01/2026-06-06_1339_formatI/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d3_formatI/r01/2026-06-06_1339_formatI/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d3_formatI/r01/2026-06-06_1339_formatI/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_recover_both/l4_checked_action_surface/d3_formatI/r01/2026-06-06_1339_formatI/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
