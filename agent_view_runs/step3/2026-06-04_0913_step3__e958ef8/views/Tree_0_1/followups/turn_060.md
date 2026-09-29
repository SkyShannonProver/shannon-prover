## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Where:**
- setup before the frontier (positions 1–9) — absorb with `sp`/`wp`: 10 setup statement(s): SplitC2.I1.RO.m <- empty; SplitC2.I2.RO.m <- empty; () <-
- frontier: both sides at `k <$ dkey`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling (e.g. `t0{1} = t1{2}`), the smt lemmas.

## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {x : unit, r, b, b0, b1, b2, b3 : bool, k : key}
&2 (right) : {b, b0, b1 : bool}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

SplitC2.I1.RO.m <- empty   ( 1)  Mem.log <- empty         
SplitC2.I2.RO.m <- empty   ( 2)  Mem.lc <- []             
() <- x                    ( 3)  BNR.lenc <- []           
SplitC1.I2.RO.m <- empty   ( 4)  BNR.ndec <- 0            
SplitD.ROF.RO.m <- empty   ( 5)                           
k <$ dkey                  ( 6)                           
Mem.k <- k                 ( 7)                           
Mem.log <- empty           ( 8)                           
Mem.lc <- []               ( 9)                           
BNR.lenc <- []             (10)                           
BNR.ndec <- 0              (11)                           

post =
  (true /\
   (glob A){1} = (glob A){2} /\
   inv_cpa SplitC2.I1.RO.m{1} SplitC2.I2.RO.m{1} Mem.log{1} Mem.log{2} Mem.
     lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\
   forall (n : nonce) (c : C.counter),
     (n, c) \in SplitD.ROF.RO.m{1} => n \in BNR.lenc{1}) &&
  forall (result_L result_R : bool) (A_L : (glob A)) (lenc_L : nonce list)
    (ndec_L : int) (lc_L : ciphertext list) (log_L : (ciphertext,
    plaintext) fmap) (m_L : (nonce * C.counter, poly_in) fmap)
    (m_L0 : (nonce * C.counter, poly_out) fmap) (m_L1 : (nonce * C.counter,
    block) fmap) (A_R : (glob A)) (lenc_R : nonce list) (ndec_R : int)
    (lc_R : ciphertext list) (log_R : (ciphertext, plaintext) fmap),
    (result_L = result_R /\
     A_L = A_R /\
     inv_cpa m_L m_L0 log_L log_R lc_L lc_R lenc_L lenc_R ndec_L ndec_R /\
     forall (n : nonce) (c : C.counter), (n, c) \in m_L1 => n \in lenc_L) =>
    result_L = result_R
[383|check]>
```

## Status
remaining **1** · phase `relational_program` / `procedure_body`

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
- you submitted: `commit_tactic` `proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set).`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":60,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"proc; inline*; auto; rewrite /inv_cpa /=; smt(get_setE mem_set)."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"711 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/step3_l4_compare/l4_checked_action_surface/chacha_step3/r01/2026-06-04_0913_step3/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
