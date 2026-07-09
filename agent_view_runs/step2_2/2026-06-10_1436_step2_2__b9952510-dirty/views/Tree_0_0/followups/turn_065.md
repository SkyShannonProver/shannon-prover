## 🎯 Current Goal
```
Current goal (remaining: 3)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
&1 (left ) : {r : bool}
&2 (right) : {r, forged : bool, i : int, n : nonce, ns : nonce list,
             r0 : poly_in, s : poly_out, bl : block}

pre =
  ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
  forged{2} = false /\
  i{2} = 0 /\ Mem.lc{1} = Mem.lc{2} /\ StLSke.gs{1} = RO.m{2}


post =
  (0 <= i{2} <= size ns{2} /\
   Mem.lc{1} = Mem.lc{2} /\
   StLSke.gs{1} = RO.m{2} /\
   ns{2} = undup (map (fun (p : ciphertext) => p.`1) Mem.lc{2}) /\
   forall (c : ciphertext),
     c \in Mem.lc{2} =>
     dec StLSke.gs{1} Mem.k{1} c <> None<:nonce * associated_data * bytes> =>
     c.`1 \in take i{2} ns{2} => forged{2}) /\
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
[323|check]>
```

## Status
remaining **3** · phase `relational_program` / `procedure_entry`

### Need more? submit one of these read-only requests
- No fresh recommendation is available for an equivalence goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "equiv_bridge_lemmas"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
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

**Last action:** `move: Hdec Hc Hn0; rewrite /dec /genpoly1305 /get /=; case: c => cn ca cc ct /=…` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/rerun_struct_core/l4_checked_action_surface/step2_2/r01/2026-06-10_1436_step2_2/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
