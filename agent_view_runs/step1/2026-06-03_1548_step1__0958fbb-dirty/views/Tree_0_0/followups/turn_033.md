## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {k : key, n : nonce, p0 : bytes, a : associated_data,
             c0 : message, t, t' : tag,
             nact : nonce * associated_data * message * tag, c : ciphertext,
             p : plaintext option,
             result : (nonce * associated_data * bytes) option}
&2 (right) : {n : nonce, p : bytes, a : associated_data, c : message,
             t, t' : tag, nact : nonce * associated_data * message * tag,
             result : (nonce * associated_data * bytes) option}

pre =
  result{2} = None /\
  (n{2}, a{2}, c{2}, t{2}) = nact{2} /\
  k{1} = Mem.k{1} /\
  nact{1} = c{1} /\
  result{1} = None /\
  (n{1}, a{1}, c0{1}, t{1}) = nact{1} /\
  c{1} = nact{2} /\ Mem.k{1} = IndBlock.k{2}

t' <@                                     (1)  t' <@                               
  Poly(OpCCinit.OCC(I_stateless)).mac(k,  ( )    D(A, IndBlock).O.Poly.mac(n, a, c)
    n, a, c0)                             ( )                                      

post =
  t'{1} = t'{2} /\
  t{1} = t{2} /\
  n{1} = n{2} /\
  a{1} = a{2} /\
  c0{1} = c{2} /\
  result{1} = result{2} /\ k{1} = IndBlock.k{2} /\ Mem.k{1} = IndBlock.k{2}
[307|check]>
```

## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `named_handle_not_callable_in_current_view`; so step into the body or write a manual invariant.

**Candidate:**
- `poly_mac1` (`call poly_mac1.`)

**Frontier:**
- frontier: both sides at `t' <@ Poly(OpCCinit.OCC(I_stateless)).mac(k, n, a, c0)`
- frontier: both sides at `no matching left-side call at this frontier`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

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
- you submitted: `commit_tactic` `proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq 1 1 : (t'{1} = t'{2…`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":33,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"proc. inline{1} GenChaChaPoly(OpCCinit.OCC(I_stateless)).dec. sp. seq 1 1 : (t'{1} = t'{2} /\\ t{1} = t{2} /\\ n{1} = n{2} /\\ a{1} = a{2} /\\ c0{1} = c{2} /\\ result{1} = result{2} /\\ k{1} = IndBlock.k{2} /\\ Mem.k{1} = IndBlock.k{2})."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"270 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun4_l1l4_90min/l4_checked_action_surface/chacha_step1/r01/2026-06-03_1548_step1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
