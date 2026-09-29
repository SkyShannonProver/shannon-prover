## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
------------------------------------------------------------------------
Context : hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
Bound   : [=] 1%r

pre = j = 0 /\ PIR.s' = [] /\ PIR.s = [] /\ i = i0


post =
  (0 <= j <= N /\
   i = i0 /\
   big predT<:int> a PIR.s +^ big predT<:int> a PIR.s' =
   if i0 < j then a i0 else zerow) /\
  forall (s1 s' : int list) (j0 : int),
    ((0 <= j0 <= N /\
      i = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     N - j0 <= 0 => ! j0 < N) /\
    (! j0 < N =>
     (0 <= j0 <= N /\
      i = i0 /\
      big predT<:int> a s1 +^ big predT<:int> a s' =
      if i0 < j0 then a i0 else zerow) =>
     big predT<:int> a s1 +^ big predT<:int> a s' = a i0)
[35|check]>
```

## Status
remaining **1** · phase `procedure_frontier` / `procedure_body`

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
- Mid-proof suffix may need indexed `wp` to absorb a tail before a cut.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp` or `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken the pre/postcondition before closing.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- A sampling step may need `rnd` to reduce it to a distribution/probability fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `rewrite /predT in H; smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
