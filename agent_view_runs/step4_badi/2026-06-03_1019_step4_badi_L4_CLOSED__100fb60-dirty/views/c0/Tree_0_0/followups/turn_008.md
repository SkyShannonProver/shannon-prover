## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
nth0: int
H: 0 <= nth0 < qdec
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b : bool, i0 : int}

pre = (glob A){1} = (glob A){2} /\ i0{2} = nth0

UFCMA_l.lbad1 <- []                  (1)  UFCMA_li.cbadi <- 0                
UFCMA.cbad1 <- 0                     (2)  UFCMA_li.badi <- false             
b <@                                 (3)  UFCMA_li.i <- i0                   
  CPA_game(CCA_CPA_Adv(BNR_Adv(A)),  ( )                                     
    UFCMA_l.O).main()                ( )                                     
                                     (4)  UFCMA_l.lbad1 <- []                
                                     (5)  UFCMA.cbad1 <- 0                   
                                     (6)  b <@                               
                                     ( )    CPA_game(CCA_CPA_Adv(BNR_Adv(A)),
                                     ( )      UFCMA_li.O).main()             

post =
  (let tt = nth (w1, w2) UFCMA_l.lbad1{1} nth0 in tt.`1 = tt.`2) => UFCMA_li.
  badi{2}
[421|check]>
```

## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `named_handle_not_callable_in_current_view`; so step into the body or write a manual invariant.

**Candidate:**
- `UFCMA_genCC` (`call UFCMA_genCC.`)

**Frontier:**
- setup before the frontier (positions 1–2) — absorb with `sp`/`wp`: 2 setup statement(s): UFCMA_l.lbad1 <- []; UFCMA.cbad1 <- 0
- frontier: both sides at `b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), UFCMA_l.O).main()`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## Status
remaining **3** · phase `failure_diagnostic` / `call_site`

### Need more? submit one of these read-only requests
- proof-state analysis has a dataflow invariant skeleton, but the generated oracle/residual obligations are only classifi…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals"}}`
- A tactic or probe failed and the latest error needs classification.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `probe_tactic` `inline*.`
- result: Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.

```json
{"turn":8,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"inline*."}},"ok":true,"manager_note":"Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"459 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `tmp/wt/badi_l4/artifacts/eval_suite/step4_badi_l4_opus48/l4_checked_action_surface/chacha_step4_badi/r01/2026-06-03_1019_step4_badi/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
