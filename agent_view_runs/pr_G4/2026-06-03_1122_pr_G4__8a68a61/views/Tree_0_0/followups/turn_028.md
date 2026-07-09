## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}
Bound   : [<=] (PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)

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

post = (g ^ G1.u, G1.g_ ^ G1.u', g ^ r', g ^ r) \in G3.cilog
[147|check]>
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
remaining **4** · phase `procedure_frontier` / `procedure_body`

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
- you submitted: `commit_tactic` `seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order …`
- result: Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.

```json
{"turn":28,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"seq 13 : (size G3.cilog <= PKE_.qD) 1%r ((PKE_.qD%r / order%r) ^ 3 * (PKE_.qD%r / (order - 1)%r)) 0%r 1%r."}},"ok":true,"manager_note":"Commit attempt did not change the committed EasyCrypt proof state; use the returned result and latest view before trying the next proof intent.","manager_actions":[{"action":"probability budget risky commit repair","outcome":"The manager did not commit this tactic because route health marks it as risky under the product probability budget."}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
