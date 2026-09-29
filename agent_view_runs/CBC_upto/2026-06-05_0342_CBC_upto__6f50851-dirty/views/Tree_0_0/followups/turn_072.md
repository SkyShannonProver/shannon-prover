## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
f_eq: equiv[ DoubleQuery(PRFi).f  ~ DoubleQuery(Sample).f :
              (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
              (!DoubleQuery.bad{2} =>
               arg{1} = arg{2} /\
               DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
               fdom PRFi.m{1} = DoubleQuery.qs{1}) ==>
              (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
              (!DoubleQuery.bad{2} =>
               res{1} = res{2} /\
               DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
               fdom PRFi.m{1} = DoubleQuery.qs{1})]
------------------------------------------------------------------------
&1 (left ) : {i : int, s, pi : block, p, c : block list} [programs are in sync]
&2 (right) : {i : int, s, pi : block, p, c : block list}

pre =
  (i{1} = i{2} /\ p{1} = p{2}) /\
  0 <= i{1} <= size p{1} /\
  (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
  (!DoubleQuery.bad{2} =>
   c{1} = c{2} /\
   s{1} = s{2} /\
   DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
   fdom PRFi.m{1} = DoubleQuery.qs{1})


post =
  (((i{1} = i{2} /\ p{1} = p{2}) /\
    0 <= i{1} <= size p{1} /\
    (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
    (!DoubleQuery.bad{2} =>
     c{1} = c{2} /\
     s{1} = s{2} /\
     DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
     fdom PRFi.m{1} = DoubleQuery.qs{1})) /\
   (i{1} < size p{1} <=> i{2} < size p{2})) /\
  forall (bad_L : bool) (qs_L : block fset) (m_L : (block, block) fmap)
    (c_L : block list) (i_L : int) (s_L : block) (bad_R : bool)
    (qs_R : block fset) (c_R : block list) (i_R : int) (s_R : block),
    ! i_L < size p{1} =>
    ! i_R < size p{2} =>
    (i_L = i_R /\ p{1} = p{2}) /\
    0 <= i_L <= size p{1} /\
    (bad_L <=> bad_R) /\
    (!bad_R => c_L = c_R /\ s_L = s_R /\ qs_L = qs_R /\ fdom m_L = qs_L) =>
    if bad_R then bad_L <=> bad_R
    else c_L = c_R /\ qs_L = qs_R /\ (bad_L <=> bad_R) /\ fdom m_L = qs_L
[144|check]>
```

## Status
remaining **4** · phase `relational_program` / `verification_residue`

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
- you submitted: `commit_tactic` `sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0).`
- result: Committed tactic accepted; the EasyCrypt proof state changed.

```json
{"turn":72,"handled_intent":{"intent":"commit_tactic","payload":{"tactic":"sp 1 1; wp; exists* DoubleQuery.bad{2}; elim* => B0; call (f_eqM B0); auto; smt(size_ge0)."}},"ok":true,"manager_note":"Committed tactic accepted; the EasyCrypt proof state changed.","manager_actions":[{"action":"tactic commit","outcome":"EasyCrypt accepted the committed tactic.","timing":"290 ms"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
