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

## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** call (_: true). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** framework reads the head as left=`assignment` right=`assignment` (both_sides_at_assignment) — find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (see structural_checkpoints).

## Status
remaining **1** · phase `failure_diagnostic` / `call_site`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `call (_: true).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] invalid last instruction`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `swap{1} 7 -5.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
