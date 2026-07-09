## 🎯 Current Goal
```
Current goal

Type variables: <none>

k0: key
n0: nonce
p0: message
gs0: globS
Hnil: forall (s : block), take_xor [] s = []
&hr: {i : int, c : byte list, k : key, n : nonce, z : block, p : message}
eqk: k{hr} = k0
eqn: n{hr} = n0
eqp: p{hr} = p0
eqgs: OCC.gs{hr} = gs0
------------------------------------------------------------------------
(k{hr} = k0 /\
 n{hr} = n0 /\
 OCC.gs{hr} = gs0 /\
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p{hr} =
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
forall (c0 : byte list) (i0 : int) (p1 : message),
  (k{hr} = k0 /\
   n{hr} = n0 /\
   OCC.gs{hr} = gs0 /\
   1 <= i0 /\
   c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
   size p1 <= 0 => p1 = []) /\
  (p1 = [] =>
   k{hr} = k0 /\
   n{hr} = n0 /\
   OCC.gs{hr} = gs0 /\
   1 <= i0 /\
   c0 ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
   gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0 =>
   c0 = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0)
[214|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `hr`
- `OCC.gs`
- `gen_CTR_encrypt_bytes`
- `take_xor`
- `cc`
- `byte`
- `list`
- `i0`

**Visible hypotheses:**
- `Hnil: forall (s : block), take_xor [] s = []`
- `eqk: k{hr} = k0`
- `eqn: n{hr} = n0`
- `eqp: p{hr} = p0`
- `eqgs: OCC.gs{hr} = gs0`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **1** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `move=> &hr /= [eqk [eqn [eqp eqgs]]].` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
