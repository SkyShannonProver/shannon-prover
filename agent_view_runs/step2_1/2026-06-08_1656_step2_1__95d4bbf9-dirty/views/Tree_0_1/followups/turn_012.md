## 🎯 Current Goal
```
Current goal (remaining: 4)

Type variables: <none>

&m: {}
------------------------------------------------------------------------
forall &2,
  (p{2}.`1, p{2}.`2,
   gen_CTR_encrypt_bytes take_xor
     (fun (_ : key) (n : nonce) (c0 : C.counter) => oget StLSke.gs{2}.[n, c0])
     Mem.k{2} p{2}.`1 1 p{2}.`3,
   genpoly1305
     (fun (_ : key) (n : nonce) (c0 : C.counter) => oget StLSke.gs{2}.[n, c0])
     Mem.k{2} p{2}.`1
     (topol p{2}.`2
        (gen_CTR_encrypt_bytes take_xor
           (fun (_ : key) (n : nonce) (c0 : C.counter) =>
              oget StLSke.gs{2}.[n, c0]) Mem.k{2} p{2}.`1 1 p{2}.`3))) =
  enc StLSke.gs{2} Mem.k{2} p{2}
[298|check]>
```

## ⚠️ Recover — your last committed tactic was REJECTED

**Rejected:** by move=> &2; rewrite /enc /get /=. — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step.

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
- pure_tail_surface is visible for the current goal
- current proof state has no program-frontier work before the logical residual

**Available local work:**
- pure tail obligation families: `map_update_projection`, `constructor_projection`, `quantified_residual_logic`
- map update lookup cases: `n, c0`

**Limitations:**
- does not select a destructor, witness, rewrite, or SMT lemma
- reported checkpoints are recovery references, not a default route

**Yours:** match your head (above) to a row, then YOU pick the condition / branch / invariant. Do NOT retry the same family that was just rejected. If genuinely stuck, `undo_to_checkpoint` (see structural_checkpoints).

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- The latest transition recorded an error.
  submit `{"intent": "inspect_context", "payload": {"topic": "diagnose"}}`
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `by move=> &2; rewrite /enc /get /=.` — EasyCrypt rejected the committed tactic. Use the error summary and current goal to revise the proof step. (The committed EasyCrypt proof state was not changed.)
**EasyCrypt error:** `[by]: cannot close goals`

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `inline *; wp; skip => />.` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
