## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &1 &2,
  (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m} =>
  (forall (xR : ZModE.exp), xR \in dt => xR = xR) &&
  forall (sk0L : ZModE.exp),
    sk0L \in dt =>
    sk0L = sk0L &&
    (forall (yR : ZModE.exp), yR \in dt => yR = yR) &&
    forall (yL : ZModE.exp),
      yL \in dt =>
      yL = yL &&
      (g ^ sk0L = g ^ sk0L /\ (glob A){1} = (glob A){2}) &&
      forall (result_L result_R : ptxt * ptxt) (A_L A_R : (glob A)),
        result_L = result_R /\ A_L = A_R =>
        forall (bL : bool),
          bL \in {0,1} =>
          ((g ^ yL = g ^ yL /\
            (g ^ sk0L ^ yL * if bL then result_L.`2 else result_L.`1) =
            g ^ (sk0L * yL) * if bL then result_R.`2 else result_R.`1) /\
           A_L = A_R) &&
          forall (result_L0 result_R0 : bool) (A_L0 A_R0 : (glob A)),
            result_L0 = result_R0 /\ A_L0 = A_R0 =>
            (result_L0 = bL) = (result_R0 = bL)
[30|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `ZModE.exp`
- `dt`
- `result_R`
- `ptxt`
- `A_L`
- `A_R`
- `bool`
- `result_R0`

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **1** · phase `relational_program` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
