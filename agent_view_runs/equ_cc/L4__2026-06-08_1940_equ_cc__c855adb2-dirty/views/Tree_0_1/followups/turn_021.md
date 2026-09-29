## Pure Logic — close with smt / rewrite

**Goal operators:**
- `block`
- `dblock`
- `extend`
- `take`
- `size`
- `bytes_of_block`
- `oget`
- `SplitD.ROF.RO.m`

**Visible hypotheses:**
- `hsz: size p{1} = size p{2}`
- `hi: 1 <= i{2}`
- `hbnd: size c{2} + size p{1} <= max_cipher_size`
- `hdisj: p{1} = [] \/ size c{2} = (i{2} - 1) * block_size`
- `hp1: p{1} <> []`
- `hp2: p{2} <> []`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
&1: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
    x, x0 : nonce * C.counter, z, result, r, r0 : block, p : message}
&2: {i : int, c : byte list, n : nonce, z : block, p : message}
hsz: size p{1} = size p{2}
hi: 1 <= i{2}
hbnd: size c{2} + size p{1} <= max_cipher_size
hdisj: p{1} = [] \/ size c{2} = (i{2} - 1) * block_size
hc1: forall (c0_0 : C.counter),
       (n0, c0_0) \in SplitD.ROF.RO.m{1} => C.toint c0_0 < i{2}
hc2: forall (n1 : nonce) (c0_0 : C.counter),
       (n1, c0_0) \in SplitD.ROF.RO.m{1} => n1 = n0 \/ (n1 \in BNR.lenc{1})
hp1: p{1} <> []
hp2: p{2} <> []
------------------------------------------------------------------------
(forall (zR : block),
   zR \in dblock => zR = extend p{1} +^ (extend p{1} +^ zR)) =>
forall (r0L : block),
  r0L \in dblock =>
  r0L = extend p{1} +^ (extend p{1} +^ r0L) /\
  (r0L = extend p{1} +^ (extend p{1} +^ r0L) =>
   (c{2} ++
    take (size p{1})
      (bytes_of_block
         (extend p{1} +^
          oget
            SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L].[n0, C.ofintd i{2}])) =
    c{2} ++ take (size p{2}) (bytes_of_block (extend p{1} +^ r0L)) /\
    size (drop block_size p{1}) = size (drop block_size p{2}) /\
    1 <= i{2} + 1 /\
    size
      (c{2} ++
       take (size p{1})
         (bytes_of_block
            (extend p{1} +^
             oget
               SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L].[n0, C.ofintd
                                                                    i{2}]))) +
    size (drop block_size p{1}) <= max_cipher_size /\
    (drop block_size p{1} = [] \/
     size
       (c{2} ++
        take (size p{1})
          (bytes_of_block
             (extend p{1} +^
              oget
                SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L].[n0, C.ofintd
                                                                    i{2}]))) =
     i{2} * block_size) /\
    (forall (c00 : C.counter),
       (n0, c00) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L] =>
       C.toint c00 < i{2} + 1) /\
    forall (n1 : nonce) (c00 : C.counter),
      (n1, c00) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L] =>
      n1 = n0 \/ (n1 \in BNR.lenc{1})) /\
   (drop block_size p{1} = [] => drop block_size p{2} = []) /\
   (drop block_size p{2} = [] => drop block_size p{1} = []))
[371|check]>
```

## Status
remaining **2** · phase `relational_program` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `move=> zR _; smt(Block.addK Block.MB.addmA Block.MB.add0m Block.MB.addmC).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
