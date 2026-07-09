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
(m0, m1) <@ A.choose(pk)    (4)  gy <- g ^ y                    
b <$ {0,1}                  (5)  gz <- g ^ (x * y)              
pk0 <- pk                   (6)  (m0, m1) <@ A.choose(gx)       
m <- if b then m1 else m0   (7)  b0 <$ {0,1}                    
c <- (g ^ y, pk0 ^ y * m)   (8)  b' <@                          
                            ( )    A.guess(gy,                  
                            ( )      gz * if b0 then m1 else m0)
b' <@ A.guess(c)            (9)  b <- b' = b0                   

post = (b'{1} = b{1}) = b{2}
[23|check]>
```

## Call Frontier

**Situation:** no named-call candidate at this frontier.

**Frontier:**
- setup before the frontier (positions 3–3) — absorb with `sp`/`wp`: (pk, sk) <- (g ^ sk0, sk0)
- frontier: both sides at `(m0, m1) <@ A.choose(pk)`
- frontier: both sides at `b' <@ A.guess(c)`
- frontier: both sides at `y <$ dt`
- frontier: left side only at `sk0 <$ dt`
- frontier: right side only at `x <$ dt`
- frontier: left side only at `b <$ {0,1}`

**Options:**
- `call (_: <Inv>)` — relate the two calls under a relational invariant `<Inv>`
- `inline*` / `proc` — step into the callee body
- `swap` / `transitivity` / `eager` — reorder or commute a statement ACROSS the call (an eager argument; see `tactic_forms` for the exact `eager`/`swap` shape)

**Yours:** which family fits this goal — relate the call, step into it, or reorder a statement across it.

## Status
remaining **1** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `swap{1} 7 -5.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
