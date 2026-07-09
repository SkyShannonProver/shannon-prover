## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
&m0: {r : bool}
z: int
&hr: {r, forged : bool, i : int, n : nonce, ns : nonce list,
     x : nonce * C.counter, r0 : poly_in, s : poly_out, bl : block}
Hlt: i{hr} < size ns{hr}
Hz: size ns{hr} - i{hr} = z
i_rng: 0 <= i{hr} <= size ns{hr}
Hlc: Mem.lc{m0} = Mem.lc{hr}
Hgs: StLSke.gs{m0} = RO.m{hr}
Hns: ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})
IH: forall (c : ciphertext),
      c \in Mem.lc{hr} =>
      dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i{hr} ns{hr} => forged{hr}
------------------------------------------------------------------------
0 <= i{hr} + 1 <= size ns{hr} /\
Mem.lc{m0} = Mem.lc{hr} /\
StLSke.gs{m0} = RO.m{hr} /\
ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr}) /\
forall (c : ciphertext),
  c \in Mem.lc{hr} =>
  dec StLSke.gs{m0} Mem.k{m0} c <> None<:nonce * associated_data * bytes> =>
  c.`1 \in take (i{hr} + 1) ns{hr} =>
  forged{hr} ||
  test_poly (nth witness<:nonce> ns{hr} i{hr}) Mem.lc{hr}
    (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`1
    (mk_rs (oget RO.m{hr}.[nth witness<:nonce> ns{hr} i{hr}, C.ofintd 0])).`2
[318|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `size`
- `ns`
- `Mem.lc`
- `m0`
- `StLSke.gs`
- `RO.m`
- `undup`

**Visible hypotheses:**
- `Hlt: i{hr} < size ns{hr}`
- `Hz: size ns{hr} - i{hr} = z`
- `i_rng: 0 <= i{hr} <= size ns{hr}`
- `Hlc: Mem.lc{m0} = Mem.lc{hr}`
- `Hgs: StLSke.gs{m0} = RO.m{hr}`
- `Hns: ns{hr} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{hr})`

**Alignment gap to feed smt:** [{"signal": "local_membership_decomposition_available", "confidence": "medium", "gap": "Visible membership sources carry local case facts that can expose the key, projection, or witness relation, but those source facts …

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

_Need richer context? `inspect_context` topics: `goal_info` · `lemma_hints` · `tactic_forms` (+name) — submit `{"intent": "inspect_context", "payload": {"topic": "<one>", …}}` (topics marked `(+arg)` need that extra field)._

**Last action:** `split; last by smt(); do 4! (split; first by smt()).` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
