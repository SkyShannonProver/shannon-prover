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

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `gen_CTR_encrypt_bytes`
- `take_xor`
- `key`
- `nonce`
- `c0`
- `C.counter`
- `oget`
- `StLSke.gs`

**Memory translation:**
- memories in play: `{2}`
- Decorations identify the program memory from which a term is read.

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **4** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `inline *; wp; skip => />.` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/medium4_l1_l4noprobe/l4_checked_action_surface/chacha_step2_1/r01/2026-06-08_1656_step2_1/iteration_1/node_memory/Tree_0_1/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
