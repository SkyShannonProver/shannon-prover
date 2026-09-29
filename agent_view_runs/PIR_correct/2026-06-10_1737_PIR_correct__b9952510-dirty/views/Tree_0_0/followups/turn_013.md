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

pre = i = i0

(1)  j <- 0                     
(2)  (PIR.s, PIR.s') <- ([], [])

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
[30|check]>
```

**Last action:** `move: hinv; rewrite /predT /= => hinv; smt(xorwA xorwC xorw0 xorwK).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/pir_correct/r01/2026-06-10_1737_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/pir_correct/r01/2026-06-10_1737_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/pir_correct/r01/2026-06-10_1737_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_iclass/l1_goal_projection/pir_correct/r01/2026-06-10_1737_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
