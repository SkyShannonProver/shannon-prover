## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {x : unit, r, b, b0, b1, b2, b3 : bool, k : key}
&2 (right) : {b, b0, b1 : bool}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

SplitC2.I1.RO.m <- empty                     ( 1)  Mem.log <- empty                      
SplitC2.I2.RO.m <- empty                     ( 2)  Mem.lc <- []                          
() <- x                                      ( 3)  BNR.lenc <- []                        
SplitC1.I2.RO.m <- empty                     ( 4)  BNR.ndec <- 0                         
SplitD.ROF.RO.m <- empty                     ( 5)  b1 <@                                 
                                             (  )    A(BNR(CPA_CCA_Orcls(EncRnd))).main()
k <$ dkey                                    ( 6)                                        
Mem.k <- k                                   ( 7)                                        
Mem.log <- empty                             ( 8)                                        
Mem.lc <- []                                 ( 9)                                        
BNR.lenc <- []                               (10)                                        
BNR.ndec <- 0                                (11)                                        
b3 <@                                        (12)                                        
  A(                                         (  )                                        
    BNR(                                     (  )                                        
      CPA_CCA_Orcls(                         (  )                                        
        RealOrcls(                           (  )                                        
          GenChaChaPoly(                     (  )                                        
            CCRO(SplitD.                     (  )                                        
              RO_DOM(SplitC1.                (  )                                        
                RO_Pair(SplitC2.             (  )                                        
                  RO_Pair(SplitC2.I1.        (  )                                        
                    RO, SplitC2.I2.RO),      (  )                                        
                  SplitC1.I2.RO),            (  )                                        
                SplitD.ROF.RO))))))).main()  (  )                                        

post = b3{1} = b1{2}
[363|check]>
```

## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `named_handle_not_callable_in_current_view`; so step into the body or write a manual invariant.

**Candidate:**
- `pair`

**Frontier:**
- setup before the frontier (positions 1–9) — absorb with `sp`/`wp`: 10 setup statement(s): SplitC2.I1.RO.m <- empty; SplitC2.I2.RO.m <- empty; () <-
- frontier: both sides at `b3 <@ A( BNR( CPA_CCA_Orcls( RealOrcls( GenChaChaPoly( CCRO(`
- frontier: both sides at `k <$ dkey`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## Status
remaining **1** · phase `seq_cut` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current cut or frontier context may expose a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- The visible cut may depend on LHS/RHS statement alignment or missing live facts.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`
- Need the valid form for call, seq, while, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The visible cut/frontier may need indexed `sp i j` before branch tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
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
- you submitted: `commit_tactic` `wp.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":11,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"wp."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"2.0 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
