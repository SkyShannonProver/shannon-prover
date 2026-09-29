## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &m0,
  hoare[ k0 <- k; ...; x <- (n1, c4) :
          c2 = c1{m0} /\
          n = n{m0} /\
          a = a{m0} /\
          p0 = p0{m0} /\
          Mem.log = Mem.log{m0} /\
          Mem.lc = Mem.lc{m0} /\
          BNR.lenc = BNR.lenc{m0} /\
          BNR.ndec = BNR.ndec{m0} /\
          ! (n \in BNR.lenc) /\
          (forall (nn : nonce) (ci : C.counter),
             (nn, ci) \in SplitC2.I1.RO.m => nn \in BNR.lenc) /\
          (forall (nn : nonce) (ci : C.counter),
             (nn, ci) \in SplitC2.I2.RO.m => nn \in BNR.lenc) /\
          forall (nn : nonce) (ci : C.counter),
            (nn, ci) \in SplitD.ROF.RO.m => nn \in n :: BNR.lenc ==>
          SplitD.test x]
[380|check]>
```

## Pure Logic — close with smt / rewrite

**Goal shape:** quantified ambient tail

**Obligation families:**
- `map_membership_preservation` — The remaining membership obligation relates an updated map key to a list or set membershi… (NOT: The surface reports the alignment facts currently visible; it does no…)
- `quantified_residual_logic` — The current proof point is dominated by local logical obligations rather than program-fro… (seen: universal quantifier visible; implication residual visible) (NOT: Quantifier names are not normalized across EasyCrypt pretty-printer v…)

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition.

## Status
remaining **5** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `probe_tactic` `by auto; smt(C.ofintdK C.gt0_max_counter).`
- result: Accepted closing/checking probe. Commit the exact tactic only if you want to try closing or checking this obligation.

```json
{"turn":35,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"by auto; smt(C.ofintdK C.gt0_max_counter)."}},"ok":true,"manager_note":"Accepted closing/checking probe. Commit the exact tactic only if you want to try closing or checking this obligation.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"544 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
