## 🎯 Current Goal
```
Current goal (remaining: 5)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
Context : hr: {b0 : bool, e, f, h : group, r, r' : ZModE.exp,
              m0, m1 : PKE_.plaintext}

pre = size G3.cilog <= size G1.log /\ size G1.log <= PKE_.qD

(1)  G1.u <$ dt               
(2)  G1.u' <$ dt \ pred1 G1.u 
(3)  r' <$ dt                 
(4)  r <$ dt                  
(5)  G3.a <- g ^ G1.u         
(6)  G3.a_ <- G1.g_ ^ G1.u'   
(7)  G3.c <- g ^ r'           
(8)  G3.d <- g ^ r            

post = size G3.cilog <= PKE_.qD
[145|check]>
```

## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** experts decompose this shape as case split then rcond swap wp conseq → local smt.

**Where:**
- setup before the frontier (positions 5–8) — absorb with `sp`/`wp`: 4 setup statement(s): G3.a <- g ^ G1.u; G3.a_ <- G1.g_ ^ G1.u'; G3.c <- g ^ r'; 
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
- you submitted: `commit_tactic` `auto; smt(PKE_.qD_pos).`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":22,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"auto; smt(PKE_.qD_pos)."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"608 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/prg4_l4_opus48/l4_checked_action_surface/cs_pr_G4/r01/2026-06-03_1122_pr_G4/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
