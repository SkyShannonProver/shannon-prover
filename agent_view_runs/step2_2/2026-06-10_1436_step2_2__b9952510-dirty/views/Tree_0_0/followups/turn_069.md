## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
&1: {r : bool}
&2: {r, forged : bool, i : int, n : nonce, ns : nonce list, r0 : poly_in,
    s : poly_out, bl : block}
Hns: ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})
Hf: forged{2} = false
Hi: i{2} = 0
Hlc: Mem.lc{1} = Mem.lc{2}
Hgs: StLSke.gs{1} = RO.m{2}
------------------------------------------------------------------------
forall (forged_R : bool) (i_R : int),
  ((0 <= i_R <= size ns{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    StLSke.gs{1} = RO.m{2} /\
    ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
    forall (c : ciphertext),
      c \in Mem.lc{2} =>
      dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i_R ns{2} => forged_R) =>
   size ns{2} - i_R <= 0 => ! i_R < size ns{2}) /\
  (! i_R < size ns{2} =>
   (0 <= i_R <= size ns{2} /\
    Mem.lc{1} = Mem.lc{2} /\
    StLSke.gs{1} = RO.m{2} /\
    ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
    forall (c : ciphertext),
      c \in Mem.lc{2} =>
      dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i_R ns{2} => forged_R) =>
   (exists (c : ciphertext),
      (c \in Mem.lc{1}) /\
      dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>) =>
   forged_R)
[325|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `bool`
- `i_R`
- `int`
- `size`
- `ns`
- `Mem.lc`
- `StLSke.gs`
- `RO.m`

**Visible hypotheses:**
- `Hns: ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})`
- `Hf: forged{2} = false`
- `Hi: i{2} = 0`
- `Hlc: Mem.lc{1} = Mem.lc{2}`
- `Hgs: StLSke.gs{1} = RO.m{2}`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Memory translation:**
- memories in play: `{1}`, `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **3** · phase `relational_program` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `call_site_options` · `call_invariant_skeleton` · `call_subgoals` (+invariant) · `tactic_forms` (+name) · `align` — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `move=> &1 &2 [Hns [Hf [Hi [Hlc Hgs]]]]; split; first by rewrite Hi; smt(size_ge…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
