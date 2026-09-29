## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
i0: int
hi0: 0 <= i0 < N
z: int
&hr: {b : bool, i, j : int, s, s0 : int list, r, r' : word}
H: (((0 <= j{hr} <= N /\
      i{hr} = i0 /\
      big (fun (_ : int) => true) a PIR.s{hr} +^
      big (fun (_ : int) => true) a PIR.s'{hr} =
      if i0 < j{hr} then a i0 else zerow) /\
     j{hr} < N) /\
    N - j{hr} = z) /\
   true
v: bool
hv: v \in {0,1}
hji: j{hr} = i{hr}
hv2: v
------------------------------------------------------------------------
N - (j{hr} + 1) < z
[32|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`

**Visible hypotheses:**
- `hi0: 0 <= i0 < N`
- `H: (((0 <= j{hr} <= N /\`
- `hv: v \in {0,1}`
- `hji: j{hr} = i{hr}`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `smt(BBS.big_cons xorwA xorwC xorw0 xorwK).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_iclass/l4_checked_action_surface/pir_correct/r01/2026-06-10_1742_PIR_correct/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
