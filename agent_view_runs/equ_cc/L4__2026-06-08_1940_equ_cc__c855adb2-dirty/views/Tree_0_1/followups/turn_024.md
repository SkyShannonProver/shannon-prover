## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** split; last by smt(size_drop size_eq0 size_ge0). — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

**Head now:** read your goal's first instruction (after `~`, below the `==>`), then find its row below.

**Head to tactic:**
- head `if` (same guard both sides) -> `if`.
- head `if` (divergent guard) -> `case: (<cond>)` then `rcondt{i} N` / `rcondf{i} N`.
- head `while` -> `while (<inv>)`; force the guard with `rcondt`/`rcondf`; never `while(true)` without a variant.
- head assignment `x <- e` -> `sp` / `wp`.
- head sample `x <$ d` -> `rnd`.
- head `call` -> `call (<invariant>)`, or `inline*`/`proc` to step into the body first.
- `invalid first instruction` / `right instruction list is not empty` = a side STILL HAS CODE: you cannot `skip`/`auto`/`sim`/`conseq`-close yet -> reduce the head with the matching tactic above (or `sp`/`wp` to consume statements first).

**Evidence:**
- membership source shapes: concat_membership, map_update_membership
- map update keys: n0, C.ofintd i{2}
- membership fact: (n0, c0_0) \in SplitD.ROF.RO.m{1} => C.toint c0_0 < i{2}

**Available local work:**
- pure tail obligation families: `sampling_bijection`, `map_update_projection`, `map_membership_preservation`, `quantified_residual_logic`
- membership decomposition sources: `concat_membership`, `map_update_membership`
- map update lookup cases: `n0, C.ofintd i{2}`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (see structural_checkpoints).

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
hbij: forall (zR : block),
        zR \in dblock => zR = extend p{1} +^ (extend p{1} +^ zR)
r0L: block
hr0L: r0L \in dblock
------------------------------------------------------------------------
(c{2} ++ take (size p{1}) (bytes_of_block (extend p{1} +^ r0L)) =
 c{2} ++ take (size p{2}) (bytes_of_block (extend p{1} +^ r0L)) /\
 size (drop block_size p{1}) = size (drop block_size p{2}) /\
 1 <= i{2} + 1 /\
 size (c{2} ++ take (size p{1}) (bytes_of_block (extend p{1} +^ r0L))) +
 size (drop block_size p{1}) <= max_cipher_size /\
 (drop block_size p{1} = [] \/
  size (c{2} ++ take (size p{1}) (bytes_of_block (extend p{1} +^ r0L))) =
  i{2} * block_size) /\
 (forall (c00 : C.counter),
    (n0, c00) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L] =>
    C.toint c00 < i{2} + 1) /\
 forall (n1 : nonce) (c00 : C.counter),
   (n1, c00) \in SplitD.ROF.RO.m{1}.[n0, C.ofintd i{2} <- r0L] =>
   n1 = n0 \/ (n1 \in BNR.lenc{1})) /\
(drop block_size p{1} = [] => drop block_size p{2} = []) /\
(drop block_size p{2} = [] => drop block_size p{1} = [])
[373|check]>
```

## Status
remaining **2** · phase `relational_program` / `ambient_logic`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
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

**Last action:** `split; last by smt(size_drop size_eq0 size_ge0).` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[error] cannot prove goal (strict)`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> _; rewrite !get_set_sameE /=.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/chachapoly_l1_l4noprobe/l4_checked_action_surface/equ_cc/r01/2026-06-08_1940_equ_cc/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
