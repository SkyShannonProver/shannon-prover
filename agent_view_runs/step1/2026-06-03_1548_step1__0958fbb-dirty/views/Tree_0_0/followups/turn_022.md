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
- you submitted: `lookup_symbol`
- result: Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.

```json
{"turn":22,"handled_intent":{"intent":"lookup_symbol","payload":{"symbol":"RealOrcls"}},"ok":true,"manager_note":"Read-only context. Accepted/rejected tactic or call text inside a preview is route-selection information, not the current proof-state error.","manager_actions":[{"action":"symbol lookup","outcome":"The manager returned read-only context for the current goal.","timing":"1.0 s","content":{"preview":"[WHERE-HIT] RealOrcls (kind: module) * In [modules]: module RealOrcls(S : SKE) = { proc init() : unit = { S.init(); Mem.k <@ S.kg(); } proc enc(p : plaintext) : ciphertext = { var c : ciphertext; c <@ S.enc(Mem.k, p); return c; } proc dec(c : ciphertext) : plaintext option = { var p : plaintext option; p <@ S.dec(Mem.k, c); return p; } }."}}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
