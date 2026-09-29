## Surgery — align or decompose the two sides

**Where:**
- setup before the frontier — absorb with `sp`/`wp`: no left-side setup before this frontier
- frontier: left side only at `z <@ CCRO( SplitD.RO_DOM( SplitC1.RO_Pair( SplitC2. RO_Pair(`
- frontier: left side only at `no matching left-side sample at this frontier`

**Toolbox:**
- `case: (<which guard>)` — split the divergent branch (YOU pick the condition).
- `rcondt{i} N` / `rcondf{i} N` — force a branch (YOU pick t/f); for a loop guard, `while(true); auto`.
- `swap [a..b] c` — line up statement order across the two sides.
- `wp` / `wp -N -N` — absorb suffix statements (from the end) before `call`/`sim`.
- `conseq(:_==> ={<the few equal vars>})` then `sim` — weaken to the equal prefix and auto-close it.
- local `smt(...)` for the residual logic.

**Yours:** which condition to `case` on, which way each guard resolves, the sample coupling, the smt lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
------------------------------------------------------------------------
&1 (left ) : {i : int, c : byte list, k : key, n : nonce, z : block,
             p : message}
&2 (right) : {i : int, c : byte list, n : nonce, z : block, p : message}

pre =
  (c{1} = c{2} /\
   i{1} = i{2} /\
   n{1} = n0 /\
   size p{1} = size p{2} /\
   1 <= i{1} /\
   size c{1} + size p{1} <= max_cipher_size /\
   (p{1} = [] \/ size c{1} = (i{1} - 1) * block_size) /\
   mr0 = ROin.m{1} /\
   ms0 = ROout.m{1} /\
   (forall (c0 : C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1}) /\
   forall (n1 : nonce) (c0 : C.counter),
     (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\
  p{1} <> [] /\ p{2} <> []

z <@                                      (1)  z <$ dblock                            
  CCRO(                                   ( )                                         
    SplitD.RO_DOM(                        ( )                                         
             SplitC1.RO_Pair(             ( )                                         
                       SplitC2.           ( )                                         
                       RO_Pair(           ( )                                         
                         SplitC2.I1.RO,   ( )                                         
                         SplitC2.I2.RO),  ( )                                         
                       SplitC1.I2.RO),    ( )                                         
             SplitD.ROF.RO)).cc(k, n,     ( )                                         
    C.ofintd i)                           ( )                                         
c <-                                      (2)  c <-                                   
  c ++                                    ( )    c ++ take (size p) (bytes_of_block z)
  take (size p)                           ( )                                         
    (bytes_of_block (extend p +^ z))      ( )                                         
p <- drop block_size p                    (3)  p <- drop block_size p                 
i <- i + 1                                (4)  i <- i + 1                             

post =
  (c{1} = c{2} /\
   i{1} = i{2} /\
   n{1} = n0 /\
   size p{1} = size p{2} /\
   1 <= i{1} /\
   size c{1} + size p{1} <= max_cipher_size /\
   (p{1} = [] \/ size c{1} = (i{1} - 1) * block_size) /\
   mr0 = ROin.m{1} /\
   ms0 = ROout.m{1} /\
   (forall (c0 : C.counter), (n0, c0) \in ROF.m{1} => C.toint c0 < i{1}) /\
   forall (n1 : nonce) (c0 : C.counter),
     (n1, c0) \in ROF.m{1} => n1 \in n0 :: BNR.lenc{1}) /\
  (p{1} = [] <=> p{2} = [])
[358|check]>
```

## Status
remaining **2** · phase `relational_program` / `call_site`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `while (c{1} = c{2} /\ i{1} = i{2} /\ n{1} = n0 /\ size p{1} = size p{2} /\ 1 <=…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
