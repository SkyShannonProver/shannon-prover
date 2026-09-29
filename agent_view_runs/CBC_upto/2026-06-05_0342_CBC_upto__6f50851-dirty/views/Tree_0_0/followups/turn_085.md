## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
&2: {}
bad: DoubleQuery.bad{2}
------------------------------------------------------------------------
pre = true

    CBC_Oracle(DoubleQuery(PRFi)).enc {&1}
    [=] 1%r

post = true
[150|check]>
```

## ⚠️ Deep Surgery — decompose, don't grind the whole goal

**Route:** decompose this large goal; don't transform the whole thing at once.

**Toolbox:**
- `case:` the divergent branch, then `rcondt`/`rcondf` to force guards.
- `conseq(:_==> ={<few equal vars>})` + `sim` on the identical prefix.
- `wp` (incl. `wp -N -N`) to absorb tails before `call`/`sim`.

**Yours:** which guard to `case`/`rcond`, the coupling, the smt lemmas.

## Status
remaining **3** · phase `procedure_frontier` / `procedure_body`

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
- you submitted: `probe_tactic` `proc; while (0 <= i <= size p) (size p - i).`
- result: Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.

```json
{"turn":85,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"proc; while (0 <= i <= size p) (size p - i)."}},"ok":true,"manager_note":"Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"1.7 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
