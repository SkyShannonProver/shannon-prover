## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

_mk: mK
_ek: block
_c: block list
------------------------------------------------------------------------
Context : hr: {b : bool, i : int, ek, s, ci, pi : block,
              c, padded : block list, t : tag, p' : msg,
              pt : (msg * tag) option, mk : mK, p : msg option,
              key : block * mK}
Bound   : [=] 1%r

pre =
  exists (c0 : block list),
    p = None /\
    (ek, mk) = key /\
    s = head witness c0 /\
    c = behead c0 /\
    padded = [] /\ i = 0 /\ (key, c0).`1 = (_ek, _mk) /\ (key, c0).`2 = _c

(1--)  while (i < size c) {            
(1.1)    ci <- nth witness c i         
(1.2)    pi <@ PRPc.PseudoRP.fi(ek, ci)
(1.3)    padded <- padded ++ [s - pi]  
(1.4)    s <- ci                       
(1.5)    i <- i + 1                    
(1--)  }                               

post =
  padded = cbc_dec AESi _ek (head witness _c) (behead _c) /\
  mk = _mk /\ p = None
[225|check]>
```

## Status
remaining **4** · phase `procedure_frontier` / `procedure_body`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
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
- you submitted: `commit_tactic` `auto.`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/smoke_mee_decrypt_correct/l4_checked_action_surface/mee_decrypt_correct/r01/2026-06-06_0130_mee_decrypt_correct/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
