## 🎯 Current Goal (unchanged)
```
Current goal

Type variables: <none>

k0: key
n0: nonce
p0: message
gs0: globS
```
_…(+29 more lines — goal unchanged this turn; full goal in `LEGAL_LATEST_WORKSPACE_VIEW`)_

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
- Need parsed goal shape, resolved names, or KB pattern hints.
  submit `{"intent": "inspect_context", "payload": {"topic": "goal_info"}}`
- Need local or standard-library lemma names before rewriting a pure goal.
  submit `{"intent": "inspect_context", "payload": {"topic": "lemma_hints"}}`
- Need the valid EasyCrypt form for rewrite, apply, conseq, while, or SMT setup.
  submit `{"intent": "inspect_context", "payload": {"topic": "tactic_forms", "name": "rewrite"}}`

_(full untruncated view: `latest_workspace_view.json`)_

**Last action:** `split; first by rewrite eqk eqn eqgs eqp /=. move=> c0 i0 p1; split; first by s…` — EasyCrypt accepted this read-only probe. The committed proof state was not changed; `goal_after_probe` shows the goal that would be visible if this tactic were committed. (The committed EasyCrypt proof state was not changed.)

## Already tried at this exact state
_(your own history at this goal + EasyCrypt's verdict — facts, not a prohibition; you decide whether a re-try is worth it)_
- commit `move=> &hr /= [eqk [eqn [eqp eqgs]]].` → accepted

---

Submit exactly ONE proof intent via the `submit_proof_intent` MCP tool (only `intent` + `payload`; no node ids, hashes, request ids, or reasoning fields).

### Legal Node Memory Anchor

LEGAL_NODE_MEMORY_DIR: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0`
LEGAL_LATEST_WORKSPACE_VIEW: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_workspace_view.json`
LEGAL_LATEST_MANAGER_RESULT: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_manager_result.json`
LEGAL_LATEST_FOLLOWUP: `artifacts/eval_suite/wave1_rerun_l4/l4_checked_action_surface/d0_chacha_spec/r01/2026-06-06_1533_chacha_spec/iteration_1/node_memory/Tree_0_0/latest_followup.md`

Compaction recovery: if these exact paths are missing from your context, refresh through `submit_proof_intent` with `{"intent":"inspect_context","payload":{"topic":"goal_info"}}` instead of using shell directory discovery for proof-state artifacts.

The current goal is shown in full above. Only-if-needed: the complete structured view (every collapsed panel) is in `LEGAL_LATEST_WORKSPACE_VIEW`.
