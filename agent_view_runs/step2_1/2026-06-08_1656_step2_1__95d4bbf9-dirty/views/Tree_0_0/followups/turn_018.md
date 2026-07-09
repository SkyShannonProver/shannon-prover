## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {b : bool, k : key, x, x0 : nonce * C.counter,
             l : NonceCount.t list, r : block} [programs are in sync]
&2 (right) : {b : bool, k : key, x, x0 : nonce * C.counter,
             l : NonceCount.t list, r : block}

pre = (glob A){1} = (glob A){2}

(1----)  l <- NonceCount.enum                    
(2----)  RO.m <- empty<:nonce * C.counter, block>
(3----)  while (l <> []) {                       
(3.1--)    x <- head witness<:NonceCount.t> l    
(3.2--)    x0 <- x                               
(3.3--)    r <$ dblock                           
(3.4--)    if (x0 \notin RO.m) {                 
(3.4.1)      RO.m <- RO.m.[x0 <- r]              
(3.4--)    }                                     
(3.5--)    l <- behead l                         
(3----)  }                                       

post =
  (forall (kR : key), kR \in dkey => kR = kR) &&
  forall (kL : key),
    kL \in dkey =>
    kL = kL &&
    ((glob A){1} = (glob A){2} /\ kL = kL /\ RO.m{1} = RO.m{2}) &&
    forall (result_L result_R : bool) (A_L A_R : (glob A)),
      result_L = result_R /\ A_L = A_R /\ kL = kL /\ RO.m{1} = RO.m{2} =>
      result_L = result_R
[302|check]>
```

## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** sim. — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** framework reads the head as left=`assignment` right=`None` (one-sided_frontier) — find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Evidence:**
- recent `sim` rejection
- visible branch/sampling/frontier mismatch

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `map_update_projection`, `map_membership_preservation`, `quantified_residual_logic`
- membership decomposition sources: `map_update_membership`
- map update lookup cases: `x0`
- residual program surgery

**Limitations:**
- does not prescribe a conseq, sim, wp, or skip script
- reports residual program evidence before pure-tail obligations

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (see structural_checkpoints).

## Status
remaining **2** · phase `relational_program` / `verification_residue`

_Need richer context? `inspect_context` topics: `diagnose` · `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `sim.` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot infer the set of equalities`
**⚠️ I could not read a proof intent from the last message. Please reply with exactly one JSON object like: {"intent": "probe_tactic", "payload": {"tactic": "..."}} or {"intent": "inspect_context", "payload": {"topic": "goal_info"}}**

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `inline *; auto.` → accepted
- commit `sim.` → REJECTED: [error] cannot infer the set of equalities

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
