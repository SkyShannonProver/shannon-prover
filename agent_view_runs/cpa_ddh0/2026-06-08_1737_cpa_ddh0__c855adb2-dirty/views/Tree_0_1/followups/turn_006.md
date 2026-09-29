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
b' <@ A.guess(c)            (9)                                 

post = (b'{1} = b{1}) = (b'{2} = b0{2})
[24|check]>
```

## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier (positions 3–3) — absorb with `sp`/`wp`: (pk, sk) <- (g ^ sk0, sk0)
- frontier: both sides at `(m0, m1) <@ A.choose(pk)`
- frontier: both sides at `b' <@ A.guess(c)`
- frontier: both sides at `y <$ dt`
- frontier: left side only at `sk0 <$ dt`
- frontier: right side only at `x <$ dt`
- frontier: left side only at `b <$ {0,1}`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## Status
remaining **1** · phase `seq_cut` / `call_site`

### Need more? submit one of these read-only requests
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The current cut or frontier context may expose a call route.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- The visible cut may depend on LHS/RHS statement alignment or missing live facts.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`
- Need the valid form for call, seq, while, rnd, or rewrite.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The visible cut/frontier may need indexed `sp i j` before branch tactics.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "sp"}}`
- Mid-proof pRHL suffix surgery may need indexed `wp`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "wp"}}`
- Statement order may need a small `swap` before `sp`, `wp`, or `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "swap"}}`
- A guarded branch may need `rcondt` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondt"}}`
- A guarded branch may need `rcondf` after a case split or invariant fact.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rcondf"}}`
- A suffix proof may need `conseq` to weaken to a smaller relation before `sim`.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "conseq"}}`
- One side may have an extra sample or need an explicit sample coupling.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rnd"}}`
- A known statement-order mismatch may need an eager/lazy transformation.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "eager"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `wp.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/elgamal_cpa_ddh0/r01/2026-06-08_1737_cpa_ddh0/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
