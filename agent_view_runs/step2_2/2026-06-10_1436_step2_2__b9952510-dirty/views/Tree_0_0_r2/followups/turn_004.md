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
forged_R: bool
i_R: int
Hexit: ! i_R < size ns{2}
i_rng: 0 <= i_R <= size ns{2}
Hlc': Mem.lc{1} = Mem.lc{2}
Hgs': StLSke.gs{1} = RO.m{2}
Hns': ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})
IH: forall (c : ciphertext),
      c \in Mem.lc{2} =>
      dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
      c.`1 \in take i_R ns{2} => forged_R
c: ciphertext
Hc: c \in Mem.lc{1}
Hdec: dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes>
------------------------------------------------------------------------
forged_R
[327|check]>
```

## Pure Logic — close with smt / rewrite

**Visible hypotheses:**
- `Hns: ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2})`
- `Hf: forged{2} = false`
- `Hi: i{2} = 0`
- `Hlc: Mem.lc{1} = Mem.lc{2}`
- `Hgs: StLSke.gs{1} = RO.m{2}`
- `Hexit: ! i_R < size ns{2}`

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

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- The visible frontier contains call sites or named equiv handles may apply.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_site_options"}}`
- You are at an abstract-adversary `call (_: <inv>)` and want the mechanical glob frame of the invariant before adding yo…
  submit `{"intent": "inspect_context", "payload": {"topic": "call_invariant_skeleton"}}`
- You are considering `call (_: Inv)` and already have a concrete invariant expression you want to test first.
  submit `{"intent": "inspect_context", "payload": {"topic": "call_subgoals", "invariant": "<the EasyCrypt invariant expression inside call (_: ...)>"}}`
- A tactic has multiple EasyCrypt argument forms.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "call"}}`
- The frontier may need indexed `sp i j` before branch or call tactics.
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
- LHS/RHS statement order may need swap/alignment context.
  submit `{"intent": "inspect_context", "payload": {"topic": "align"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `move=> Hexit [i_rng [Hlc' [Hgs' [Hns' IH]]]] [c [Hc Hdec]].` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0_r2`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0_r2/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0_r2/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0_r2/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
