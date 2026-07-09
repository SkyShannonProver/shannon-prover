## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}

pre = true

( 1)  G1.log <- []                                    
( 2)  G3.cilog <- []                                  
( 3)  G1.cstar <- None                                
( 4)  G1.w <$ dt \ pred1 zero                         
( 5)  G1.g_ <- g ^ G1.w                               
( 6)  G1.k <$ dk                                      
( 7)  G1.y <$ dt                                      
( 8)  f <- g ^ G1.y                                   
( 9)  G1.z <$ dt                                      
(10)  h <- g ^ G1.z                                   
(11)  G1.x <$ dt                                      
(12)  e <- g ^ G1.x                                   
(13)  (m0, m1) <@ G4.A.choose(G1.k, g, G1.g_, e, f, h)
(14)  G1.u <$ dt                                      
(15)  G1.u' <$ dt \ pred1 G1.u                        
(16)  r' <$ dt                                        
(17)  r <$ dt                                         
(18)  G3.a <- g ^ G1.u                                
(19)  G3.a_ <- G1.g_ ^ G1.u'                          
(20)  G3.c <- g ^ r'                                  
(21)  G3.d <- g ^ r                                   

post = true
[139|check]>
```

## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Where:**
- setup before the frontier (positions 10–12) — absorb with `sp`/`wp`: 2 setup statement(s): h <- g ^ G1.z; e <- g ^ G1.x
- frontier: both sides at `(m0, m1) <@ G4.A.choose(G1.k, g, G1.g_, e, f, h)`
- frontier: both sides at `G1.x <$ dt`
- frontier: both sides at `G1.u <$ dt`
- frontier: both sides at `G1.u' <$ dt \ pred1 G1.u`
- frontier: both sides at `r' <$ dt`
- frontier: both sides at `r <$ dt`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## Status
remaining **5** · phase `procedure_frontier` / `procedure_body`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current procedure frontier exposes a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- Need the valid form for call, while, seq, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- valid `sp` forms and common traps
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Need the valid one-sided hoare/phoare loop form.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "while"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `inspect_context`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":7,"handled_intent":{"intent":"inspect_context","payload":{"topic":"goal_info"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"inspect goal info","outcome":"The manager returned read-only context for the current goal.","timing":"1.5 s","content":{"title":"Parsed Goal Information","goal_info":{"goal_type":"hoare","num_remaining":5,"num_remaining_determined":true,"remaining_goals_note":"You have 5 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 4 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress.","remaining_goals_inference":[{"subgoal_n":1,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `seq`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":2,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `seq`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":3,"predicted_type":"(carried-over from earlier branching)","description":"Pending subgoal from a branching tactic earlier in history; this entry isn't from the latest `seq`. Run -goal-info on each subgoal as you reach it to see its actual shape.","origin_tactic":"(earlier branching, not tracked)"},{"subgoal_n":4,"predicted_type":"(inherits prior goal type)","description":"Prefix 0..K (pre -> post after first K stmts)","origin_tactic":"seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order -"},{"subgoal_n":5,"predicted_type":"(inherits prior goal type)","description":"Suffix K..end (post after K -> final post)","origin_tactic":"seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order -"}],"remaining_goals_inference_caveat":"These subgoal shapes are INFERRED from the last branching tactic's known pattern, NOT read from EC directly (EC's emacs output only exposes the current goal). Use as hints, not ground truth. Ground truth is obtained by closing the current subgoal and running -goal-info on the next. Known-wrong cases: 3-arg `call (_: bad, Inv)`, nested branchers, while-variants with different arg counts."},"goal_state":{"state_kind":"open","goal_type":"hoare","num_remaining":5,"num_remaining_determined":true,"proof_candidate_closed":false,"active_goal_hash":"abb7983d4cef771dbc68ed7cbfa8ab590cbff20e","authority":"pretty_text_fallback","ec_ground_truth":false},"history":{"tactic_count":3,"has_qed":false,"latest_tactic":"seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 1%r 1%r 0%r."},"latest_transition":{"kind":"decomposition","status":"ok","goals_before":1,"goals_after":5,"candidate_closed":false,"no_progress":false,"tactic":"seq 21 : ((G3.a, G3.a_, G3.c, G3.d) \\in G3.cilog) ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 1%r 1%r 0%r."},"notes":[{"message":"You have 5 subgoals pending. The `goal_type` above is for the CURRENT (first pending) goal ONLY \u2014 the other 4 subgoal(s) may have DIFFERENT types. This is normal after tactics like `call (_: Inv)`, `byequiv`, `conseq`, or `seq K:` which each generate multiple subgoals with mixed pRHL/phoare/hoare/ambient shapes. Do NOT interpret a mismatch between the current-goal type and your proof plan as 'session is broken'. Close the current subgoal, then inspect the next one via `-goal-info` again. Use `-status` to see total proof progress."}]}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
