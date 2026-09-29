## 🎯 Current Goal
```
Current goal

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b, b' : bool, sk0, y : ZModE.exp, pk, pk0 : pkey, sk : skey,
             m0, m1, m : ptxt, c : ctxt}
&2 (right) : {b, b0, b' : bool, gy, gz : group, x, y : ZModE.exp, gx : pkey,
             m0, m1 : ptxt}

pre = (glob A){2} = (glob A){m} /\ (glob A){1} = (glob A){m}

sk0 <$ dt                   (1)  x <$ dt                  
y <$ dt                     (2)  y <$ dt                  
(pk, sk) <- (g ^ sk0, sk0)  (3)  gx <- g ^ x              
                            (4)  gy <- g ^ y              
                            (5)  gz <- g ^ (x * y)        

post =
  (pk{1} = gx{2} /\ (glob A){1} = (glob A){2} /\ true) &&
  forall (result_L result_R : ptxt * ptxt) (A_L A_R : (glob A)),
    result_L = result_R /\ A_L = A_R /\ true =>
    (forall (b0R : bool), b0R \in {0,1} => b0R = b0R) &&
    forall (bL : bool),
      bL \in {0,1} =>
      bL = bL &&
      ((g ^ y{1}, pk{1} ^ y{1} * if bL then result_L.`2 else result_L.`1) =
       (gy{2}, gz{2} * if bL then result_R.`2 else result_R.`1) /\
       A_L = A_R /\ true) &&
      forall (result_L0 result_R0 : bool) (A_L0 A_R0 : (glob A)),
        result_L0 = result_R0 /\ A_L0 = A_R0 /\ true =>
        (result_L0 = bL) = (result_R0 = bL)
[28|check]>
```

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 3–3) — absorb with `sp`/`wp`: (pk, sk) <- (g ^ sk0, sk0)
- frontier: both sides at `y <$ dt`
- frontier: left side only at `sk0 <$ dt`
- frontier: right side only at `x <$ dt`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **1** · phase `seq_cut` / `procedure_body`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_subgoals` (+invariant) · `align` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `call (_: true).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
