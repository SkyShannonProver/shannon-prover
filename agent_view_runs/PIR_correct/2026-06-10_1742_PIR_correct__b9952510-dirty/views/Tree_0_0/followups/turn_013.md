## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `big`
- `predT`
- `int`
- `PIR.s`
- `zerow`
- `weight`
- `bool`

**Visible hypotheses:**
- `hi0: 0 <= i0 < N`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
z: int
------------------------------------------------------------------------
forall &hr,
  (((0 <= j{hr} <= N /\
     i{hr} = i0 /\
     big predT<:int> a PIR.s{hr} +^ big predT<:int> a PIR.s'{hr} =
     if i0 < j{hr} then a i0 else zerow) /\
    j{hr} < N) /\
   N - j{hr} = z) /\
  true =>
  weight {0,1} = 1%r &&
  forall (v : bool),
    v \in {0,1} =>
    predT v <=>
    if j{hr} = i{hr} then
      if v then
        let j0 = j{hr} + 1 in
        (0 <= j0 <= N /\
         i{hr} = i0 /\
         big predT<:int> a (j{hr} :: PIR.s{hr}) +^
         big predT<:int> a PIR.s'{hr} = if i0 < j0 then a i0 else zerow) /\
        N - j0 < z
      else
        let j0 = j{hr} + 1 in
        (0 <= j0 <= N /\
         i{hr} = i0 /\
         big predT<:int> a PIR.s{hr} +^
         big predT<:int> a (j{hr} :: PIR.s'{hr}) =
         if i0 < j0 then a i0 else zerow) /\
        N - j0 < z
    else
      if v then
        let j0 = j{hr} + 1 in
        (0 <= j0 <= N /\
         i{hr} = i0 /\
         big predT<:int> a (j{hr} :: PIR.s{hr}) +^
         big predT<:int> a (j{hr} :: PIR.s'{hr}) =
         if i0 < j0 then a i0 else zerow) /\
        N - j0 < z
      else
        let j0 = j{hr} + 1 in
        (0 <= j0 <= N /\
         i{hr} = i0 /\
         big predT<:int> a PIR.s{hr} +^ big predT<:int> a PIR.s'{hr} =
         if i0 < j0 then a i0 else zerow) /\
        N - j0 < z
[24|check]>
```

## Status
remaining **2** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
