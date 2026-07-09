## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

n0: nonce
mr0: (nonce * C.counter, poly_in) fmap
ms0: (nonce * C.counter, poly_out) fmap
hinv: forall (a b : block), a +^ (a +^ b) = b
&1: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
    x, x0, x1, x2, x3, x4, x5 : nonce * C.counter, r10, r4 : poly_in,
    r20, r5 : poly_out, r1 : poly, r2, r3 : extra_block,
    z, result, r, r0 : block, p : message}
&2: {i : int, c : byte list, n : nonce, z : block, p : message}
hsz: size p{1} = size p{2}
hc: size c{2} + size p{1} <= max_cipher_size
hi1: 1 <= i{1}
hcnt: i{1} - 1 + (size p{1} + block_size - 1) %/ block_size <= C.max_counter
hdom1: forall (nn : nonce) (cc : C.counter),
         (nn, cc) \in SplitD.ROF.RO.m{1} => nn = n0 \/ (nn \in BNR.lenc{1})
hdom2: forall (cc : C.counter),
         (n0, cc) \in SplitD.ROF.RO.m{1} => C.toint cc < i{1}
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
            SplitD.ROF.RO.m{1}.[n0, C.ofintd i{1} <- r0L].[n0, C.ofintd i{1}])) =
    c{2} ++ take (size p{2}) (bytes_of_block (extend p{1} +^ r0L)) /\
    size (drop block_size p{1}) = size (drop block_size p{2}) /\
    size
      (c{2} ++
       take (size p{1})
         (bytes_of_block
            (extend p{1} +^
             oget
               SplitD.ROF.RO.m{1}.[n0, C.ofintd i{1} <- r0L].[n0, C.ofintd
                                                                    i{1}]))) +
    size (drop block_size p{1}) <= max_cipher_size /\
    1 <= i{1} + 1 /\
    i{1} + (size (drop block_size p{1}) + block_size - 1) %/ block_size <=
    C.max_counter /\
    (forall (nn : nonce) (cc : C.counter),
       (nn, cc) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{1} <- r0L] =>
       nn = n0 \/ (nn \in BNR.lenc{1})) /\
    forall (cc : C.counter),
      (n0, cc) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{1} <- r0L] =>
      C.toint cc < i{1} + 1) /\
   (drop block_size p{1} = [] => drop block_size p{2} = []) /\
   (drop block_size p{2} = [] => drop block_size p{1} = []))
[378|check]>
```

**Last action:** `move=> &1 &2 hsz hc hi1 hcnt hdom1 hdom2 hp1 hp2; split; first by move=> zR _; …` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l1_goal_projection/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal above is your complete surface. `LEGAL_LATEST_WORKSPACE_VIEW` is the manager's audit file, not part of your surface — you do not need to open it.
