## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool}
&2 (right) : {b, b0 : bool}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

RealOrcls(                                   (1)  IndBlock.init()                 
  GenChaChaPoly(                             ( )                                  
    OpCCinit.OCC(I_stateless))).init()       ( )                                  
b <@                                         (2)  D(A, IndBlock).O.init()         
  A(                                         ( )                                  
    RealOrcls(                               ( )                                  
      GenChaChaPoly(                         ( )                                  
        OpCCinit.OCC(I_stateless)))).main()  ( )                                  
                                             (3)  b0 <@ A(D(A, IndBlock).O).main()
                                             (4)  b <- b0                         

post = b{1} = b{2}
[294|check]>
```

## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `residual_after_call_site`; so step into the body or write a manual invariant.

**Candidate:**
- `lemma`

**Frontier:**
- setup before the frontier (positions 1–1) — absorb with `sp`/`wp`: RealOrcls( GenChaChaPoly( OpCCinit.OCC(I_stateless))).init()
- frontier: both sides at `b <@ A( RealOrcls( GenChaChaPoly( OpCCinit.OCC(I_stateless))`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## Status
remaining **2** · phase `failure_diagnostic` / `call_site`

### Need more? submit one of these read-only requests
- A tactic or probe failed and the latest error needs classification.
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
{"turn":21,"handled_intent":{"intent":"inspect_context","payload":{"topic":"goal_info"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect goal info","outcome":"The manager returned read-only context for the current goal.","timing":"1.0 s","content":{"title":"Parsed Goal Information","goal_info":{"goal_type":"pRHL","num_remaining":2,"num_remaining_determined":true,"pre":"pre = (glob A){2} = (glob A){m} /\\ (glob A){1} = (glob A){m}","post":"post = b{1} = b{2}","left_statements":[{"pos":1,"text":"RealOrcls( GenChaChaPoly( OpCCinit.OCC(I_stateless))).init()","type":"ASSIGN","pos_path":"1","vars_read":["I_stateless","RealOrcls","OpCCinit.OCC","init","GenChaChaPoly"]},{"pos":2,"text":"b <@ A( RealOrcls( GenChaChaPoly( OpCCinit.OCC(I_stateless)))).main()","type":"CALL","pos_path":"2","procedure":"A.main","vars_written":["b"],"vars_read":["I_stateless","RealOrcls","OpCCinit.OCC","A","main","GenChaChaPoly"]}],"right_statements":[{"pos":1,"text":"IndBlock.init()","type":"ASSIGN","pos_path":"1","vars_read":["IndBlock.init"]},{"pos":2,"text":"D(A, IndBlock).O.init()","type":"ASSIGN","pos_path":"2","vars_read":["D","IndBlock","O.init","A"]},{"pos":3,"text":"b0 <@ A(D(A, IndBlock).O).main()","type":"CALL","pos_path":"3","procedure":"A.main","vars_written":["b0"],"vars_read":["D","A","O","main","IndBlock"]},{"pos":4,"text":"b <- b0","type":"ASSIGN","pos_path":"4","vars_written":["b"],"vars_read":["b0"]}],"matches":[{"left_pos":2,"right_pos":3,"match_type":"CALL","label":"A.main"}],"stmt_asymmetry":{"lhs_stmt_count":2,"rhs_stmt_count":4,"common_prefix_len":1,"one_sided_while":false,"structural_hints":["stmt count mismatch: left=2 right=4; use seq to split or swap to align","common prefix ends at position 1; divergence starts there","matched CALL pair(s) found \u2192 use `seq L R (<inv>)` to cut at same-proc calls; first candidate: seq 2 3 (<invariant>). at `A.main`"],"seq_suggestions":[{"lhs_pos":2,"rhs_pos":3,"procedure":"A.main","tactic_template":"seq 2 3 (<invariant>)."}]},"dependency_conflicts":[{"stmt_a_pos":1,"stmt_b_pos":2,"side":1,"conflict":"crosses CALL A.main"},{"stmt_a_pos":1,"stmt_b_pos":3,"side":2,"conflict":"crosses CALL A.main"},{"stmt_a_pos":1,"stmt_b_pos":4,"side":2,"conflict":"crosses CALL A.main"},{"stmt_a_pos":2,"stmt_b_pos":3,"side":2,"conflict":"crosses CALL A.main"},{"stmt_a_pos":2,"stmt_b_pos":4,"side":2,"conflict":"crosses CALL A.main"},{"stmt_a_pos":3,"stmt_b_pos":4,"side":2,"conflict":"crosses CALL A.main"}],"remaining_goals_note":"You have 2 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 1 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress."},"goal_state":{"state_kind":"open","goal_type":"pRHL","num_remaining":2,"num_remaining_determined":true,"proof_candidate_closed":false,"active_goal_hash":"b4e96b97ea8e999c395165217f547425344f5c36","authority":"pretty_text_fallback","ec_ground_truth":false},"history":{"tactic_count":6,"has_qed":false,"latest_tactic":"inline{2} D(A, IndBlock).guess."},"latest_transition":{"kind":"state_changed_same_goal_count","status":"ok","goals_before":2,"goals_after":2,"candidate_closed":false,"no_progress":false,"tactic":"inline{2} D(A, IndBlock).guess."},"items":[{"candidate":"Idiom: `call (_: <invariant>); by sim.` Do NOT include `={glob A}` in the invariant for an abstract adversary \u2014 thread it via the byequiv precondition instead.","why":"pRHL with adversary/oracle `call` and shared local invariant","verification":"not daemon-verified against the current goal"}],"notes":[{"message":"You have 2 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 1 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress."}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
