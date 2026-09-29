## Call Frontier — set up the call invariant

**Situation:** the candidate named call is NOT callable at this frontier yet — blocker: `residual_after_call_site`; so step into the body or write a manual invariant.

**Candidate:**
- `f_eq` (`call f_eq.`)

**Frontier:**
- setup before the frontier (positions 2–4.1) — absorb with `sp`/`wp`: 3 setup statement(s): c <- [s]; i <- 0; pi <- nth witness p i
- frontier: both sides at `s <@ DoubleQuery(PRFi).f(Block.(-) s pi)`
- frontier: both sides at `while (i < size p) {`
- frontier: both sides at `s <$ dBlock`

**Invariant must carry:**
- `={DoubleQuery.qs}`

**Frame facts at risk:**
- `={DoubleQuery.qs}` needed by current_goal but NOT carried by conseq #11 → rewind: submit `{"intent": "undo_to_checkpoint", "payload": {"checkpoint_id": "cp_11_47e1c8d493e3827c"}}`

**Options:**
- `call (_: <Inv>)` — cross the call with a relational invariant (YOU write `<Inv>`)
- `inline*` / `proc` — step into the callee body instead of crossing

**Yours:** the invariant predicate; whether to cross (`call`) or step in (`inline*`).

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
&1 (left ) : {i : int, s, pi : block, p, c : block list}
&2 (right) : {i : int, s, pi : block, p, c : block list}

pre =
  !DoubleQuery.bad{2} /\
  p{1} = p{2} /\
  DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
  (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
  fdom PRFi.m{1} = DoubleQuery.qs{1}

s <$ dBlock                              (1--)  s <$ dBlock                              
c <- [s]                                 (2--)  c <- [s]                                 
i <- 0                                   (3--)  i <- 0                                   
while (i < size p) {                     (4--)  while (i < size p) {                     
  pi <- nth witness p i                  (4.1)    pi <- nth witness p i                  
  s <@                                   (4.2)    s <@                                   
    DoubleQuery(PRFi).f(Block.(-) s pi)  (   )      DoubleQuery(Sample).f(Block.(-) s pi)
  c <- c ++ [s]                          (4.3)    c <- c ++ [s]                          
  i <- i + 1                             (4.4)    i <- i + 1                             
}                                        (4--)  }                                        

post =
  if DoubleQuery.bad{2} then DoubleQuery.bad{1} <=> DoubleQuery.bad{2}
  else
    c{1} = c{2} /\
    DoubleQuery.qs{1} = DoubleQuery.qs{2} /\
    (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\
    fdom PRFi.m{1} = DoubleQuery.qs{1}
[134|check]>
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
- you submitted: `probe_tactic` `seq 3 3 : (={i, p} /\ 0 <= i{1} <= size p{1} /\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2…`
- result: Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.

```json
{"turn":53,"handled_intent":{"intent":"probe_tactic","payload":{"tactic":"seq 3 3 : (={i, p} /\\ 0 <= i{1} <= size p{1} /\\ (DoubleQuery.bad{1} <=> DoubleQuery.bad{2}) /\\ (!DoubleQuery.bad{2} => c{1} = c{2} /\\ s{1} = s{2} /\\ DoubleQuery.qs{1} = DoubleQuery.qs{2} /\\ fdom PRFi.m{1} = DoubleQuery.qs{1}))."}},"ok":true,"manager_note":"Accepted structural transition probe. Decide whether to enter this phase using `last_result.structural_transition`; do not solve the speculative preview in your mental model, and do not call `undo_last_step` to undo a read-only probe.","manager_actions":[{"action":"tactic probe","outcome":"EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed.","timing":"1.4 s"}],"view_refreshed":true}
```

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/construction_gap_l1l4/l4_checked_action_surface/cbc_upto/r01/2026-06-05_0342_CBC_upto/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
