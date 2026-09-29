## 🎯 Current Goal
```
Current goal (remaining: 2)

Type variables: <none>

k0: key
n0: nonce
p0: message
gs0: globS
sz: int
&hr: {i : int, c : byte list, k, k0 : key, n, n0 : nonce, c0 : C.counter,
     z : block, p : message}
Hne: p{hr} <> []
Hsz: size p{hr} = sz
eqk: k{hr} = k0
eqn: n{hr} = n0
eqgs: OCC.gs{hr} = gs0
ge1i: 1 <= i{hr}
Heq: c{hr} ++ gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i{hr} p{hr} =
     gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0
------------------------------------------------------------------------
let p1 = drop block_size p{hr} in
let i0 = i{hr} + 1 in
(k{hr} = k0 /\
 n{hr} = n0 /\
 OCC.gs{hr} = gs0 /\
 1 <= i0 /\
 c{hr} ++
 take (size p{hr})
   (bytes_of_block
      (extend p{hr} +^ cc OCC.gs{hr} k{hr} n{hr} (C.ofintd i{hr}))) ++
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 i0 p1 =
 gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0) /\
size p1 < sz
[204|check]>
```

## Pure Logic — close with smt / rewrite

**Goal operators:**
- `p1`
- `drop`
- `block_size`
- `hr`
- `i0`
- `OCC.gs`
- `take`
- `size`

**Visible hypotheses:**
- `Hne: p{hr} <> []`
- `Hsz: size p{hr} = sz`
- `eqk: k{hr} = k0`
- `eqn: n{hr} = n0`
- `eqgs: OCC.gs{hr} = gs0`
- `ge1i: 1 <= i{hr}`

**Close with:**
- `smt(<lemmas>)` — discharge with the right lemmas (YOU pick them)
- `rewrite <eq>` / `move=> <intro>` — normalise the goal first
- `case (<cond>)` — split a disjunction / membership in the goal

**Yours:** the lemmas for `smt`, the rewrite chain, the case condition — `lookup_symbol` any operator above for its definition and lemmas.

## Status
remaining **2** · phase `ambient_logic` / `ambient_logic`

### Need more? submit one of these read-only requests
- No fresh recommendation is available; parse the current goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `move=> &hr [[H1 Hne] Hsz]; move: H1 => [eqk [eqn [eqgs [ge1i Heq]]]].` — EasyCrypt accepted the committed tactic. (The committed EasyCrypt proof state changed.)

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
