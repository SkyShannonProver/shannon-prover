## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r, forged : bool, i : int, n : nonce, ns : nonce list,
             r0 : poly_in, s : poly_out, bl : block}

pre = Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2}

                           (1--)  ns <-                                  
                           (  -)    undup                                
                           (  -)      (map (fun (p : ciphertext) => p.`1)
                           (  -)         Mem.lc)                         
                           (2--)  forged <- false                        
                           (3--)  i <- 0                                 
                           (4--)  while (i < size ns) {                  
                           (4.1)    n <- nth witness<:nonce> ns i        
                           (4.2)    bl <@ FinRO.get(n, C.ofintd 0)       
                           (4.3)    (r0, s) <- mk_rs bl                  
                           (4.4)    forged <-                            
                           (   )      forged || test_poly n Mem.lc r0 s  
                           (4.5)    i <- i + 1                           
                           (4--)  }                                      
                           (5--)  r <- forged                            

post =
  (exists (c : ciphertext),
     (c \in Mem.lc{1}) /\
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
  r{2}
[313|check]>
```

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier — absorb with `sp`/`wp`: no left-side setup before this frontier
- frontier: left side only at `no matching left-side call at this frontier`
- frontier: left side only at `no matching left-side loop at this frontier`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **3** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `equiv_bridge_lemmas` · `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `auto.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
