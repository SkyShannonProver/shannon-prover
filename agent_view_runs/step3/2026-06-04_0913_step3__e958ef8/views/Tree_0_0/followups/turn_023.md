## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `residual_after_call_site`; so step into the body or write a manual invariant.

**Candidate:**
- `equ_cc` (`exlim n{2}, ROin.m{1}, ROout.m{1} => n0 mr0 ms0; call (equ_cc n0 mr0 ms0).`)
- `lemma`

**Frontier:**
- setup before the frontier — absorb with `sp`/`wp`: no left-side setup before this frontier
- frontier: both sides at `c <@ CPA_CCA_Orcls( RealOrcls( GenChaChaPoly( CCRO(SplitD. R`
- frontier: both sides at `no matching left-side call at this frontier`
- frontier: both sides at `no matching left-side sample at this frontier`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {p : plaintext, c : ciphertext}
&2 (right) : {n : nonce, c1 : bytes, t : poly_out, a : associated_data,
             p1 : message, nap : nonce * associated_data * message,
             p, p0 : plaintext, c, c0 : ciphertext}

pre =
  (c{2} = witness /\
   c{1} = witness /\
   p{1} = p{2} /\
   inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.
     lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\
   (forall (n0 : nonce) (c2 : C.counter),
      (n0, c2) \in SplitC1.I2.RO.m{1} => n0 \in BNR.lenc{1}) /\
   forall (n0 : nonce) (c2 : C.counter),
     (n0, c2) \in SplitD.ROF.RO.m{1} => n0 \in BNR.lenc{1}) /\
  check_plaintext BNR.lenc{1} p{1}

c <@                                   (1)  p0 <- p                      
  CPA_CCA_Orcls(                       ( )                               
    RealOrcls(                         ( )                               
      GenChaChaPoly(                   ( )                               
        CCRO(SplitD.                   ( )                               
          RO_DOM(SplitC1.              ( )                               
            RO_Pair(SplitC2.           ( )                               
              RO_Pair(SplitC2.I1.RO,   ( )                               
                SplitC2.I2.RO),        ( )                               
              SplitC1.I2.RO), SplitD.  ( )                               
            ROF.RO))))).enc(p)         ( )                               
BNR.lenc <- p.`1 :: BNR.lenc           (2)  nap <- p0                    
                                       (3)  (n, a, p1) <- nap            
                                       (4)  c1 <@ EncRnd.cc(n, p1)       
                                       (5)  t <$ dpoly_out               
                                       (6)  c0 <- (n, a, c1, t)          
                                       (7)  Mem.log <- Mem.log.[c0 <- p0]
                                       (8)  c <- c0                      
                                       (9)  BNR.lenc <- p.`1 :: BNR.lenc 

post =
  c{1} = c{2} /\
  inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.
    lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\
  (forall (n0 : nonce) (c2 : C.counter),
     (n0, c2) \in SplitC1.I2.RO.m{1} => n0 \in BNR.lenc{1}) /\
  forall (n0 : nonce) (c2 : C.counter),
    (n0, c2) \in SplitD.ROF.RO.m{1} => n0 \in BNR.lenc{1}
[368|check]>
```

## Status
remaining **4** · phase `relational_program` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
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
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Manager result (previous turn)
- you submitted: `commit_tactic` `inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":23,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"inline{2} CPA_CCA_Orcls(EncRnd).enc EncRnd.enc."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"648 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
